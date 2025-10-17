using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;
using ParserModule.Visitors;

namespace CodeGenModule;

public sealed class CodeGenerator : ITopLevelStatementVisitor
{
    private readonly LLVMContextRef _context = LLVMContextRef.Global;
    private readonly LLVMModuleRef _module;
    private readonly LLVMBuilderRef _builder;
    private readonly Dictionary<string, FunctionSymbol> _functions = new();
    private readonly TypeVisitor _typeVisitor = new();

    public ExternFunctionGenerator ExternFunctionGenerator { get; }

    public CodeGenerator()
    {
        _module = LLVMModuleRef.CreateWithName("z_lang_program");
        _builder = LLVMBuilderRef.Create(LLVMContextRef.Global);
        ExternFunctionGenerator = new ExternFunctionGenerator(_module, _functions);
    }

    public static void Generate(CompilationUnit compilationUnit)
    {
        var generator = new CodeGenerator();
        foreach (var statement in compilationUnit.Statements)
        {
            statement.Accept(generator);       
        }
    }
    
    public void GenerateExternFunctionDeclaration(ExternFunctionDeclarationNode node)
    {
        ExternFunctionGenerator.Generate(node);
    }
    
    public void GenerateModuleDefinition(ModuleDefinitionNode node)
    {
        var moduleGenerator = new ModuleLevelNodeVisitor(this);
        foreach (var statement in node.Body)
        {
            statement.Accept(moduleGenerator);
        }
    }
    
    public void VisitStructImport(ImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        GenerateModuleDefinition(node);
    }

    public void VisitProgram(CompilationUnit node)
    {
        foreach (var statement in node.Statements)
        {
            statement.Accept(this);
        }
    }

    public void GenerateFunctionDefinition(FunctionDefinitionNode node)
    {
        var signature = node.Signature;
        var name = signature.Name;
        var returnType = signature.ReturnType;
        var returnTypeRef = LLVMTypeRef.Void;
        if (returnType != null)
        {
            returnType.Accept(_typeVisitor);
            returnTypeRef = _typeVisitor.Type;
        }
        
        var parameters = signature.Parameters;
        Span<LLVMTypeRef> paramTypeRefs = stackalloc LLVMTypeRef[parameters.Count];
        var scope = new Dictionary<string, LLVMValueRef>();
        for (var i = 0; i < parameters.Count; i++)
        {
            parameters[i].Type.Accept(_typeVisitor);
            paramTypeRefs[i] = _typeVisitor.Type;
        }
        
        var funcTypeRef = LLVMTypeRef.CreateFunction(returnTypeRef, paramTypeRefs, false);
        var funcValueRef = _module.AddFunction(name, funcTypeRef);
        for (var i = 0; i < parameters.Count; i++)
        {
            var paramValueRef = funcValueRef.GetParam((uint)i);
            scope.Add(parameters[i].Name, paramValueRef);
        }
        
        _functions.Add(name, new FunctionSymbol(funcTypeRef, funcValueRef));
        
        var blockRef = funcValueRef.AppendBasicBlock("entry");
        _builder.PositionAtEnd(blockRef);
        
        var body = node.Body;
        var statementVisitor = new StatementVisitor(
            _context, 
            _builder, 
            funcValueRef, 
            funcTypeRef,
            scope,
            _functions
        );
        body.Accept(statementVisitor);
    }

    public void Verify()
    {
        _module.Verify(LLVMVerifierFailureAction.LLVMPrintMessageAction);
    }

    public void SaveToFile(ReadOnlySpan<char> testAsm)
    {
        _module.PrintToFile(testAsm);
    }
}