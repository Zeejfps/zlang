using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class CodeGenerator : IAstNodeVisitor
{
    private readonly LLVMModuleRef _module;
    private readonly LLVMBuilderRef _builder;
    private readonly LLVMContextRef Context;
    private readonly Dictionary<string, LLVMValueRef> NamedValues = new();
    private readonly TypeVisitor _typeVisitor = new();

    public CodeGenerator()
    {
        _module = LLVMModuleRef.CreateWithName("z_lang_program");
        _builder = LLVMBuilderRef.Create(LLVMContextRef.Global);
    }
    
    public void VisitLiteralIntegerNode(LiteralIntegerNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBoolNode(LiteralBoolNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinaryExpression(BinaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitUnaryExpression(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifierNode(IdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
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
        for (var i = 0; i < parameters.Count; i++)
        {
            parameters[i].Type.Accept(_typeVisitor);
            paramTypeRefs[i] = _typeVisitor.Type;
        }
        
        var funcTypeRef = LLVMTypeRef.CreateFunction(returnTypeRef, paramTypeRefs, false);
        var funcRef = _module.AddFunction(name, funcTypeRef);

        var blockRef = funcRef.AppendBasicBlock("entry");
        _builder.PositionAtEnd(blockRef);
        
        var body = node.Body;
        var statementVisitor = new StatementVisitor(_builder);
        foreach (var statement in body.Statements)
        {
            statement.Accept(statementVisitor);
        }
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportNode(StructImportNode node)
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
}