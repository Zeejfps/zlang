using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class CodeGenerator : IAstNodeVisitor
{
    private readonly LLVMContextRef _context = LLVMContextRef.Global;
    private readonly LLVMModuleRef _module;
    private readonly LLVMBuilderRef _builder;
    private readonly TypeVisitor _typeVisitor = new();

    public CodeGenerator()
    {
        _module = LLVMModuleRef.CreateWithName("z_lang_program");
        _builder = LLVMBuilderRef.Create(LLVMContextRef.Global);
    }
    
    public void VisitLiteralInteger(LiteralIntegerExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinary(BinaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitUnary(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifier(IdentifierExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarAssignmentStatement(VarDefinitionStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionDeclarationNode(FunctionDefinitionNode node)
    {
        var name = node.Name;
        var returnType = node.ReturnType;
        var returnTypeRef = LLVMTypeRef.Void;
        if (returnType != null)
        {
            returnType.Accept(_typeVisitor);
            returnTypeRef = _typeVisitor.Type;
        }
        
        var parameters = node.Parameters;
        Span<LLVMTypeRef> paramTypeRefs = stackalloc LLVMTypeRef[parameters.Count];
        var scope = new Dictionary<string, LLVMValueRef>();
        for (var i = 0; i < parameters.Count; i++)
        {
            parameters[i].Type.Accept(_typeVisitor);
            paramTypeRefs[i] = _typeVisitor.Type;
        }
        
        var funcTypeRef = LLVMTypeRef.CreateFunction(returnTypeRef, paramTypeRefs, false);
        var funcRef = _module.AddFunction(name, funcTypeRef);
        for (var i = 0; i < parameters.Count; i++)
        {
            var paramValueRef = funcRef.GetParam((uint)i);
            scope.Add(parameters[i].Name, paramValueRef);
        }
        
        var blockRef = funcRef.AppendBasicBlock("entry");
        _builder.PositionAtEnd(blockRef);
        
        var body = node.Body;
        var statementVisitor = new StatementVisitor(_context, _builder, funcRef, scope);
        body.Accept(statementVisitor);
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportStatementNode(StructImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructDefinitionNode(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinitionNode(ModuleDefinitionNode node)
    {
        foreach (var function in node.Functions)
        {
            function.Accept(this);
        }
    }

    public void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void Verify()
    {
        _module.Verify(LLVMVerifierFailureAction.LLVMAbortProcessAction);
    }

    public void SaveToFile(ReadOnlySpan<char> testAsm)
    {
        _module.PrintToFile(testAsm);
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        throw new NotImplementedException();
    }
}