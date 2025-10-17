using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

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

    public void Generate(CompilationUnit compilationUnit)
    {
        
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

    public void VisitVarDefinition(VarDefinitionStatementNode node)
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

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedType(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionDefinition(FunctionDefinitionNode node)
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
        var funcRef = _module.AddFunction(name, funcTypeRef);
        for (var i = 0; i < parameters.Count; i++)
        {
            var paramValueRef = funcRef.GetParam((uint)i);
            scope.Add(parameters[i].Name, paramValueRef);
        }
        
        var blockRef = funcRef.AppendBasicBlock("entry");
        _builder.PositionAtEnd(blockRef);
        
        var body = node.Body;
        var statementVisitor = new StatementVisitor(_context, _builder, funcRef, funcTypeRef, scope);
        body.Accept(statementVisitor);
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(FunctionParameter node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImport(ImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructDefinition(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node)
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
        for (var i = 0; i < parameters.Count; i++)
        {
            parameters[i].Type.Accept(_typeVisitor);
            paramTypeRefs[i] = _typeVisitor.Type;
        }
        
        var funcTypeRef = LLVMTypeRef.CreateFunction(returnTypeRef, paramTypeRefs, false);
        _module.AddFunction(name, funcTypeRef);
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        foreach (var statement in node.Body)
        {
            statement.Accept(this);
        }
    }

    public void VisitProgram(CompilationUnit node)
    {
        foreach (var statement in node.Statements)
        {
            statement.Accept(this);
        }
    }

    public void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void Verify()
    {
        _module.Verify(LLVMVerifierFailureAction.LLVMPrintMessageAction);
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